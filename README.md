# MUSIC_VERIFICATION

## Overview
This project explores the verification of AI-generated music using neuro-symbolic reasoning. Inspired by the "Neuro-Symbolic Reasoning for Planning" paper, this tool integrates large language models (LLMs) with Satisfiability Modulo Theories (SMT) solvers to verify whether music follows Mozart's compositional style.

## Features
- **Music Generation & Verification**: AI generates music, and the SMT-based checker evaluates adherence to Mozart’s style.
- **Voice Leading & Harmony Checking**: Verifies smooth melodic motion and harmonic consistency.
- **Counterexample Feedback**: The SMT checker detects rule violations and provides feedback for AI refinement.
- **Mozart-Specific Constraints**: Ensures stylistic accuracy while allowing flexibility.

## Technologies Used
- **Music21**: Python library for music analysis and manipulation.
- **MusicXML**: Standard format for storing and processing musical scores.
- **Z3 SMT Solver**: Formal verification tool for checking compliance with music theory rules.

## Experimental Results
- **Tested on 15 Mozart compositions** → 73.3% conformed to Mozart’s style.
- **Common Violations**: Excessive melodic leaps, unexpected harmonic progressions.
- **AI Improvement**: The checker helped refine AI-generated music by identifying and correcting errors.

