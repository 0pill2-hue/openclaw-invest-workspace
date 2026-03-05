# DIRECTIVES 운영
python3 scripts/directivesdb.py init
python3 scripts/directivesdb.py import-md
python3 scripts/directivesdb.py add --id <ID> --directive "..." --due "..." --status OPEN --first_action "..." --proof "미확인"
python3 scripts/directivesdb.py start --id <ID>
python3 scripts/directivesdb.py block --id <ID> --reason "..."
python3 scripts/directivesdb.py done --id <ID> --proof "..."
python3 scripts/directivesdb.py list --status IN_PROGRESS
python3 scripts/directivesdb.py summary --top 5 --recent 5
python3 scripts/directives_gate.py --id <ID>
