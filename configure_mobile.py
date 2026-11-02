"""Prepare private VAPID keys and an explicit HTTPS origin; does not expose a port."""
import argparse
import base64
import json
import os
from pathlib import Path
from urllib.parse import urlparse


def configure(origin,contact,directory):
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    parsed=urlparse(origin)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443) or parsed.path not in ('','/') or parsed.query or parsed.fragment:raise ValueError('Use an HTTPS origin such as https://signals.example.com')
    if not contact.startswith('mailto:') or '@' not in contact:raise ValueError('Use a valid mailto: contact for the push service')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=directory/'mobile-vapid.pem'
    if path.exists():private=serialization.load_pem_private_key(path.read_bytes(),password=None)
    else:
        private=ec.generate_private_key(ec.SECP256R1())
        with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as stream:stream.write(private.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    if not isinstance(private,ec.EllipticCurvePrivateKey) or private.curve.name!='secp256r1':raise ValueError('Existing VAPID key must use P-256')
    public=private.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
    os.chmod(path,0o600)
    cfg=dict(origin='https://'+parsed.hostname,contact=contact,public_key=base64.urlsafe_b64encode(public).decode().rstrip('='),private_key_file=str(path.resolve()))
    target=directory/'mobile_push.json'
    with os.fdopen(os.open(target,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600),'w') as stream:json.dump(cfg,stream,indent=2)
    os.chmod(target,0o600)
    return target


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--origin',required=True);parser.add_argument('--contact',required=True)
    args=parser.parse_args()
    try:target=configure(args.origin,args.contact,Path.home()/'.tradingbot')
    except (ValueError,ImportError) as error:parser.exit(1,str(error)+'\nInstall requirements-mobile.txt first.\n')
    print('Configuration saved:',target);print('Restart the UI backend. Configure an authenticated HTTPS reverse proxy separately; this command does not expose your laptop.')

if __name__=='__main__':main()
