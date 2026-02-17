# PR: ci/test-workflows → main

## Link diretto

**Apri e crea PR:** https://github.com/Balizero1987/Teman2/compare/main...ci/test-workflows?expand=1

---

## Titolo PR

```
ci: workflow status badges and B1-B4 verification
```

## Body PR (copia-incolla)

```markdown
## Obiettivo

Verifica attivazione workflow GitHub Actions (B1-B4).

## Workflow inclusi

- **B1** backend-deploy.yml - Deploy Fly.io su push a main (apps/backend-rag/\*\*)
- **B2** frontend-checks.yml - Lint + build su push/PR (apps/mouth/\*\*)
- **B3a** codeql-analysis.yml - Security analysis (weekly, PR, dispatch)
- **B3b** dependabot.yml - Aggiornamenti dipendenze (pip, npm, actions)

## Modifiche

- Status badges in DEPLOYMENT_PIPELINE.md, backend/README, mouth/README
- Trivial changes per trigger path filters

## Verifica attesa

- [ ] Frontend Checks ✓ (PR tocca apps/mouth)
- [ ] CodeQL Analysis ✓ (PR verso main)
- [ ] Backend Deploy: solo al merge su main
```

---

## Comando alternativo (se `gh` funziona)

```bash
gh pr create --base main --head ci/test-workflows \
  --title "ci: workflow status badges and B1-B4 verification" \
  --body-file .github/PR_BODY.txt
```
