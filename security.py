"""Firebase ID verification using Google's published signing certificates."""
import os
import time
import threading
import httpx
import jwt
from cryptography import x509
from fastapi import HTTPException

_certs={}
_until=0
_lock=threading.Lock()

def verify_identity(bearer):
    global _certs,_until
    try:
        header=jwt.get_unverified_header(bearer)
        if header.get('alg')!='RS256' or not header.get('kid'):raise ValueError()
        with _lock:
            if time.time()>=_until:
                response=httpx.get('https://www.googleapis.com/robot/v1/metadata/x509/securetoken@system.gserviceaccount.com',timeout=10)
                response.raise_for_status()
                _certs=response.json();_until=time.time()+1800
            cert=_certs.get(header['kid'])
        if not cert:raise ValueError()
        project=os.environ.get('FIREBASE_PROJECT_ID','asmoneykit')
        key=x509.load_pem_x509_certificate(cert.encode()).public_key()
        claims=jwt.decode(bearer,key,algorithms=['RS256'],audience=project,issuer=f'https://securetoken.google.com/{project}',options={'require':['exp','iat','sub','auth_time']})
        if not claims['sub'] or len(claims['sub'])>128 or claims['auth_time']>time.time():raise ValueError()
        return {'uid':claims['sub'],'email':claims.get('email',''),'email_verified':claims.get('email_verified') is True,'signed_in':True}
    except (httpx.HTTPError,KeyError,ValueError,jwt.PyJWTError):
        raise HTTPException(401,'Sign in again. Your identity could not be verified.') from None
