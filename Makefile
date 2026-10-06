against := uv run python -m tasks

VERSION ?= dev

.PHONY: bootstrap lint test generate backtest bench evaluate replay serve demo demo-check smoke deploy rollback

bootstrap:
	$(against) bootstrap

lint:
	$(against) lint

test:
	$(against) test

generate:
	$(against) generate

backtest:
	$(against) backtest

bench:
	$(against) bench

evaluate:
	$(against) evaluate

replay:
	$(against) replay

serve:
	$(against) serve

demo:
	$(against) demo

demo-check:
	$(against) demo-check

smoke:
	DEPLOY_BASE_URL=$${DEPLOY_BASE_URL:-http://127.0.0.1:5110} uv run python -m deploy.ops smoke

rollback:
	bash deploy/vm/rollback.sh $(VERSION)

deploy:
	bash deploy/vm/deploy.sh $(VERSION)
