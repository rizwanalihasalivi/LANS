"""Retired heuristic/video demonstration, not trained-policy or ISO evidence."""
MESSAGE = 'Heuristic highway/video demo retired. It used no trained PPO and does not establish ISO compliance. Use tools/controller_review/compare.py or the documented isolated Webots pipeline; see docs/research/aris-remediation.md.'
if __name__ == '__main__':
    raise SystemExit(MESSAGE)

def __getattr__(name):
    raise AttributeError(MESSAGE)
