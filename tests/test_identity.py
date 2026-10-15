import time,unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
import jwt
import security

class IdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'test signer')])
        cls.cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(cls.key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc)-timedelta(minutes=1)).not_valid_after(datetime.now(timezone.utc)+timedelta(days=1)).sign(cls.key,hashes.SHA256()).public_bytes(serialization.Encoding.PEM).decode()
    def setUp(self):
        self.cache=patch.multiple(security,_certs={'test':self.cert},_until=time.time()+300)
        self.cache.start()
    def tearDown(self):self.cache.stop()
    def token(self,**changes):
        claims={'aud':'asmoneykit','iss':'https://securetoken.google.com/asmoneykit','sub':'user-a','iat':int(time.time()),'exp':int(time.time())+300,'auth_time':int(time.time()),'email':'test@example.com','email_verified':True}
        claims.update(changes)
        return jwt.encode(claims,self.key,algorithm='RS256',headers={'kid':'test'})
    def test_signed_identity(self):self.assertEqual(security.verify_identity(self.token())['uid'],'user-a')
    def test_wrong_project_expiry_and_future_auth_rejected(self):
        for changes in [{'aud':'other-project'},{'iss':'https://attacker.invalid'},{'exp':int(time.time())-10},{'auth_time':int(time.time())+1000}]:
            with self.assertRaises(HTTPException):security.verify_identity(self.token(**changes))
    def test_forged_signature(self):
        other=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        payload=jwt.decode(self.token(),options={'verify_signature':False})
        forged=jwt.encode(payload,other,algorithm='RS256',headers={'kid':'test'})
        with self.assertRaises(HTTPException):security.verify_identity(forged)

if __name__=='__main__':unittest.main()
