"""Verify fixed Python results before any formal timing or native mission."""
import subprocess,sys


def main():
    for module,arguments in (
        ('verify_training',('--reuse','--workers','3')),
        ('verify_evaluation',('validation','--reuse','--workers','3')),
        ('verify_evaluation',('final','--reuse','--workers','3')),
    ):
        subprocess.run([sys.executable,'-u','-m','tools.ppo_complete_v13.'+module,*arguments],check=True)


if __name__=='__main__':main()
