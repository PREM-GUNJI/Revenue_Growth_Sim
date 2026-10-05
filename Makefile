against := uv run python -m tasks

.PHONY: bootstrap lint test generate backtest bench evaluate replay serve demo demo-check smoke rollback

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
	$(against) smoke

rollback:
	$(against) rollback
