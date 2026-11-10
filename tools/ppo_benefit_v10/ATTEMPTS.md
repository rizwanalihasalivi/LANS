# Retained implementation failures

The first training launch failed while copying the old 32-unit actor's first
layer into an assumed 64-unit layer. No behavior-cloning or PPO update occurred.
All three empty traces are retained in interrupted-shape-attempt. The model now
uses the recorded old actor architecture and adds zero-weight feature columns.
The exact-transfer regression test checks local deterministic actions too.

The second launch completed all BC endpoints and one 1024-step rollout per seed,
then failed before the first PPO optimizer update. SB3 reserves info['episode']
for a Monitor statistics dictionary; the raw trace used an integer episode id.
A library-facing TrainingEnv view removes only this reserved metadata key. Raw
trace, physical transitions, observations and reward remain identical. These
3072 interrupted transitions and BC checkpoints are preserved, not counted as
successful PPO training. A real multi-rollout/optimizer-update test now exercises
the library interface. A successful fresh run retains all three fixed endpoints.

Teacher labels were reused because neither repair changes teacher collection.
The saved original collector AST is compared with the active collector, and all
core/control source hashes remain fixed. Original failed source snapshots and
logs remain available. A verifier repair is tracked separately from controller
code; snapshot hashes are checked and active mathematical dependencies must match.

The 30-input models use a new contract and a separate loader/worker. They cannot
be relabeled as the old 17-input policy. Integration must construct observations
after the current issue and preserve original packet/wall timestamps and guards.
