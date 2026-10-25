"""Retired auxiliary environment with an incompatible, unvalidated state contract.

Use envs.path_tracking_env.PathTrackingEnv for full radian steering, or
ResidualPathEnv for normalized residual actions. Old checkpoints require retraining.
Historical implementation remains in Git; no silent shape/physics alias is used.
"""
class BicycleEnv:
    def __init__(self, *args, **kwargs):
        raise RuntimeError('This auxiliary environment is retired. Use PathTrackingEnv (full steering) or ResidualPathEnv (normalized residual); see docs/research/aris-remediation.md.')

if __name__ == '__main__':
    raise SystemExit('Retired environment; see docs/research/aris-remediation.md.')
