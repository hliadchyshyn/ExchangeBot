SERVER=root@YOUR_HETZNER_IP
REMOTE_DIR=/root

.PHONY: deploy restart stop start logs status

deploy:
	scp bot.py mono.py banks.py Caddyfile $(SERVER):$(REMOTE_DIR)/
	ssh $(SERVER) "systemctl restart exchangebot"

restart:
	ssh $(SERVER) "systemctl restart exchangebot"

stop:
	ssh $(SERVER) "systemctl stop exchangebot"

start:
	ssh $(SERVER) "systemctl start exchangebot"

logs:
	ssh $(SERVER) "journalctl -u exchangebot -f"

status:
	ssh $(SERVER) "systemctl status exchangebot"
