import json, shutil, os, time
CFG='/Users/nuzantara/.openclaw/openclaw.json'
# backup chmod 0600
bak=CFG+'.bak-pre-zantara-kbli'
shutil.copy2(CFG, bak); os.chmod(bak, 0o600)
d=json.load(open(CFG))

changed=[]
# fix 1: remove contextTokens from openai-codex models
for m in d['models']['providers']['openai-codex']['models']:
    if 'contextTokens' in m:
        m.pop('contextTokens'); changed.append('removed openai-codex.contextTokens')
# fix 2: telegram.streaming {"mode":"off"} -> "off"
tg=d.get('channels',{}).get('telegram',{})
if isinstance(tg.get('streaming'), dict):
    tg['streaming']='off'; changed.append('telegram.streaming -> "off"')

# create zantara-kbli agent if absent (cloned from coder template)
ids=[a['id'] for a in d['agents']['list']]
if 'zantara-kbli' not in ids:
    coder=[a for a in d['agents']['list'] if a['id']=='coder'][0]
    z=json.loads(json.dumps(coder))   # deep copy
    z['id']='zantara-kbli'
    z['workspace']='~/.openclaw/workspace-zantara-kbli'
    z.pop('default', None)
    d['agents']['list'].append(z)
    changed.append('added agent zantara-kbli (gpt-5.5 primary, ws workspace-zantara-kbli)')

json.dump(d, open(CFG,'w'), indent=2, ensure_ascii=False)
os.chmod(CFG, 0o600)
print('CHANGES:', changed if changed else 'none (idempotent)')
