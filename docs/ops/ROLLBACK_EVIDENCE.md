# Rollback evidence

## Procedure to capture on the non-production VM

1. Deploy a known-good release with `make deploy VERSION=<v1>` and record the
   passing `make smoke` output at `http://<vm-host>:5110`.
2. Deploy a deliberately broken release `<v2>` whose `/readyz` fails. Record
   that `make deploy VERSION=<v2>` exits non-zero before it is accepted.
3. Run `make rollback VERSION=<v1>`.
4. Record the passing smoke output and `curl http://127.0.0.1:8008/model/info`
   from the VM, showing the restored model and data identifiers.

The scripts used are `deploy/vm/deploy.sh` and `deploy/vm/rollback.sh`. This
evidence must be captured on the target VM; it cannot be truthfully claimed
from a development machine without VM/Nginx/systemd access.
