# ADR: Fix per unknown

## Contesto

I test stavano fallendo a causa di connessioni al database non mockate.

## Decisione (Claude Opus 4.6)

Aggiunto mock `mock_db_pool` corretto come richiesto dalle Golden Rules.
