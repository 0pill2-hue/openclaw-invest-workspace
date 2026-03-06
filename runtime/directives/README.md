# DIRECTIVES 운영
python3 scripts/directives/db.py init
python3 scripts/directives/db.py import-md
python3 scripts/directives/db.py add --id <ID> --directive "..." --due "..." --status OPEN --first_action "..." --proof "미확인"
python3 scripts/directives/db.py start --id <ID>
python3 scripts/directives/db.py block --id <ID> --reason "..."
python3 scripts/directives/db.py done --id <ID> --proof "..."
python3 scripts/directives/db.py list --status IN_PROGRESS
python3 scripts/directives/db.py summary --top 5 --recent 5
python3 scripts/directives/gate.py --id <ID>
