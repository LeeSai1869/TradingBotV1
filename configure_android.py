"""Save optional Firebase sender configuration for the laptop. No cloud changes."""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse


def configure(origin,google_file,service_file,package_name,directory):
    parsed=urlparse(origin)
    if parsed.scheme!='https' or not parsed.hostname or parsed.port not in (None,443) or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:raise ValueError('Use the laptop HTTPS origin only')
    google=json.loads(Path(google_file).read_text());service=json.loads(Path(service_file).read_text())
    client=next((row for row in google.get('client',[]) if row.get('client_info',{}).get('android_client_info',{}).get('package_name')==package_name),None)
    if not client:raise ValueError('The Firebase Android app package does not match')
    project=google['project_info']['project_id']
    if service.get('type')!='service_account' or service.get('project_id')!=project or not service.get('private_key') or not service.get('client_email'):raise ValueError('Use the Firebase service account for the same project')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    secret=directory/'firebase-service-account.json'
    with os.fdopen(os.open(secret,os.O_CREAT|os.O_WRONLY|os.O_TRUNC,0o600),'w') as stream:json.dump(service,stream)
    os.chmod(secret,0o600)
    cfg=dict(origin='https://'+parsed.hostname,project_id=project,sender_id=google['project_info']['project_number'],app_id=client['client_info']['mobilesdk_app_id'],api_key=client['api_key'][0]['current_key'],package_name=package_name,service_account_file=str(secret.resolve()))
    path=directory/'android_push.json'
    with os.fdopen(os.open(path,os.O_CREAT|os.O_WRONLY|os.O_TRUNC,0o600),'w') as stream:json.dump(cfg,stream,indent=2)
    os.chmod(path,0o600);return path


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--origin',required=True);parser.add_argument('--google-services',required=True,type=Path);parser.add_argument('--service-account',required=True,type=Path);parser.add_argument('--package',default='com.tradingindicator.alerts');args=parser.parse_args()
    try:path=configure(args.origin,args.google_services,args.service_account,args.package,Path.home()/'.tradingbot')
    except (ValueError,KeyError,OSError) as error:parser.exit(1,str(error)+'\n')
    print('Android push configuration saved:',path);print('Restart the UI backend. No Firebase project, hosting or store listing was created.')

if __name__=='__main__':main()
