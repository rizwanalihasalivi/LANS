"""Compatibility entry point for corrected, explicitly budgeted root training.
Old checkpoints and curriculum claims are incompatible with the corrected plant.
"""
from tools.controller_review.train import main

if __name__ == '__main__':
    main()
