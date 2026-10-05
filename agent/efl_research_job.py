#!/usr/bin/env python3
"""Bounded EFL research. Source outages do not block existing daily games."""
import subprocess,sys
from pathlib import Path

def main():
    root=Path(__file__).resolve().parent
    name=sys.argv[1]
    commands={'questions':[['build_efl_bank.py']], 'players':[['transfermarkt_players.py']], 'audit':[['collect_efl_players.py','--limit','0','--audit']]}
    if name not in commands:raise SystemExit('Unknown research job')
    try:
        for command in commands[name]:
            result=subprocess.run([sys.executable,str(root/command[0]),*command[1:]],timeout=900)
            if result.returncode:print('Research incomplete; retained verified banks. Daily publisher will continue.',flush=True)
    except subprocess.TimeoutExpired:
        print('Research time budget reached; retained verified banks. Resume next run.',flush=True)

if __name__=='__main__':main()
