# TZ: Stateless fz425-agent

## Problem
sessions_send -> permanent nested session -> context overflow -> ANNOUNCE_SKIP

## Fix
Main uses sessions_spawn(agentId="fz425-agent", context="isolated", cleanup="delete")

## Files
1. /home/user1/phoenix/skills/fz425-agent/SKILL.md: replace sessions_send with sessions_spawn
2. /home/user1/phoenix/AGENTS.md: add rule "for 425-FZ use sessions_spawn, never sessions_send"

## Verify
3 questions -> all answered, no ANNOUNCE_SKIP in logs
