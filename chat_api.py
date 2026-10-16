"""HTTP conversation orchestration. Model suggestions never create approvals."""
import json
import threading
import time
from typing import Literal

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

import assistant_brain as brain


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    message: str = Field(min_length=1, max_length=4000)
    engine: Literal['local', 'armoriq'] = 'local'


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: str = Field(min_length=1, max_length=80)


def install(app, identity, perform, store, sessions, owner_lock, fingerprint):
    locks = {}
    guard = threading.Lock()
    recent = {}

    def lock_for(owner):
        with guard:
            return locks.setdefault(owner, threading.Lock())

    def require_user(user):
        if not user['signed_in']:
            raise HTTPException(401, 'Sign in to use the AI assistant. The sample tool workflow remains available.')

    def current(user):
        rows = store.source(user['uid'])[1]
        return brain.load(store, user['uid'], fingerprint(rows))

    def persist(user, conversation):
        with owner_lock(user['uid']):
            if fingerprint(store.source(user['uid'])[1]) != conversation['fingerprint']:
                raise HTTPException(409, 'Invoice data changed during this answer. Start again with the new snapshot.')
            brain.save(store, user['uid'], conversation)

    def approved(user, engine, conversation):
        with owner_lock(user['uid']):
            plan = sessions.get(user['uid'], {}).get(engine)
            return plan['tool'] if plan and plan['expires'] > time.time() and plan['fingerprint'] == conversation['fingerprint'] else None

    def action_result(tool, user, engine):
        try:
            result = perform(tool, user, engine)
            return json.loads(result.body) if isinstance(result, JSONResponse) else result
        except HTTPException as exc:
            return {'status': 'ERROR', 'reason': str(exc.detail), 'verified': False}

    def finish(user, conversation, reply, actions=None, status='CHAT'):
        item = {'role': 'assistant', 'content': reply}
        if actions:
            item['actions'] = actions
        conversation['messages'].append(item)
        persist(user, conversation)
        return {'status': status, 'reply': reply, 'actions': actions or [],
                'conversation': brain.public(conversation)}

    @app.get('/api/chat')
    def history(user=Depends(identity)):
        return brain.public(current(user))

    @app.post('/api/chat/new')
    def reset(user=Depends(identity)):
        with lock_for(user['uid']):
            conversation = brain.fresh(fingerprint(store.source(user['uid'])[1]))
            persist(user, conversation)
            return brain.public(conversation)

    @app.post('/api/agent')
    def agent(body: ChatRequest, user=Depends(identity)):
        require_user(user)
        lock = lock_for(user['uid'])
        if not lock.acquire(blocking=False):
            raise HTTPException(429, 'An answer is already being prepared. Please wait.')
        try:
            now = time.monotonic()
            calls = [stamp for stamp in recent.get(user['uid'], []) if now - stamp < 60]
            if len(calls) >= 12:
                raise HTTPException(429, 'Conversation limit reached. Wait a minute before sending more requests.')
            recent[user['uid']] = calls + [now]
            conversation = current(user)
            conversation['pending'] = None
            conversation['messages'].append({'role': 'user', 'content': body.message.strip()})
            plan_tool = approved(user, body.engine, conversation)
            messages = brain.context(conversation, body.engine, plan_tool)
            try:
                response = brain.complete(messages)
            except brain.BrainError as exc:
                raise HTTPException(exc.status, str(exc)) from None
            if not response['calls']:
                brain.add_usage(conversation, response)
                return finish(user, conversation, response['text'] or 'Could you tell me what you would like to review?')
            tool = response['calls'][0]['function']['name']
            if tool in brain.SAFE and tool != plan_tool:
                brain.add_usage(conversation, response)
                reply, _ = brain.ask_permission(conversation, tool, body.engine)
                return finish(user, conversation, reply, status='NEEDS_APPROVAL')
            if tool in brain.UNSAFE and not plan_tool:
                brain.add_usage(conversation, response)
                event = store.event(user['uid'], tool, 'BLOCKED',
                                    'No approved plan permits this simulation. Nothing executed.', engine='APPLICATION_POLICY')
                action = {'status': 'BLOCKED', 'reason': event['reason'], 'verified': False, 'event': event}
                return finish(user, conversation, action['reason'], [action], status='BLOCKED')
            action = action_result(tool, user, body.engine)
            reply = brain.explain_result(conversation, messages, response, action)
            return finish(user, conversation, reply, [action], status=action['status'])
        finally:
            lock.release()

    @app.post('/api/chat/approve')
    def approve_pending(body: ApprovalRequest, user=Depends(identity)):
        require_user(user)
        lock = lock_for(user['uid'])
        if not lock.acquire(blocking=False):
            raise HTTPException(429, 'An answer is already being prepared. Please wait.')
        try:
            conversation = current(user)
            pending = conversation.get('pending')
            if not pending or pending['id'] != body.request_id:
                raise HTTPException(409, 'This approval request expired or the invoices changed. Ask again.')
            if pending['tool'] not in brain.SAFE:
                raise HTTPException(400, 'Only supported read/draft/report tasks can be approved.')
            # Consume before provider/network work: the same card cannot execute twice.
            conversation['pending'] = None
            persist(user, conversation)
            try:
                approval = perform(pending['tool'], user, pending['engine'], approve=True,
                                   expected_fingerprint=conversation['fingerprint'])
                approval = json.loads(approval.body) if isinstance(approval, JSONResponse) else approval
            except HTTPException as exc:
                approval = {'status': 'ERROR', 'reason': str(exc.detail), 'verified': False}
            if approval.get('status') != 'APPROVED':
                return finish(user, conversation, approval.get('reason', 'Approval failed. Nothing executed.'), [approval], status='ERROR')
            action = action_result(pending['tool'], user, pending['engine'])
            # A real tool result is presented even if the second model call fails.
            proposal = {'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}}
            messages = brain.context(conversation, pending['engine'], pending['tool'])
            reply = brain.explain_result(conversation, messages, proposal, action)
            return finish(user, conversation, reply, [action], status=action['status'])
        finally:
            lock.release()
