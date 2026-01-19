-- Script per aggiornare il Telegram chat ID nel database PostgreSQL
-- Da: 8032150393
-- A: 1125336968

-- Aggiorna il chat ID nella tabella messaging_users se esiste
UPDATE messaging_users 
SET telegram_chat_id = 1125336968,
    updated_at = NOW()
WHERE telegram_chat_id = 8032150393;

-- Verifica se ci sono altri record da aggiornare
-- (aggiungi qui altre tabelle se necessario)

-- Mostra i risultati
SELECT 
    telegram_chat_id,
    user_id,
    display_name,
    verified,
    created_at
FROM messaging_users
WHERE telegram_chat_id IN (8032150393, 1125336968)
ORDER BY created_at DESC;
