"""Owner-only local account provisioning. There is no public staff/admin signup API."""
import argparse, os
from pathlib import Path
from .auth import Auth
from ..serve import ROOT

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--state',default=os.environ.get('OLV_STATE_DIR',str(ROOT/'editor/.state/backend')));p.add_argument('--origin',default=os.environ.get('OLV_EDITOR_ORIGIN','http://127.0.0.1:4180'))
    sub=p.add_subparsers(dest='action',required=True)
    invite=sub.add_parser('invite');invite.add_argument('--email',required=True);invite.add_argument('--name',required=True)
    revoke=sub.add_parser('revoke');revoke.add_argument('--email',required=True)
    args=p.parse_args();a=Auth(args.state)
    if args.action=='invite':
        token=a.invite(args.email,args.name);print(args.origin.rstrip('/')+'/signin#invite='+token)
    else:a.revoke(args.email);print('Staff access revoked, including existing sessions.')
