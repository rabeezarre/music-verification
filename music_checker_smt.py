from music21 import *
from z3 import *
from typing import List, Dict, Tuple, Set
from pathlib import Path
import json
from datetime import datetime

class MozartChecker:
    def __init__(self):
        self.solver = Solver()
        
    def extract_voice_pairs(self, score: stream.Score) -> List[Tuple[int, int, float]]:
        voice_pairs = []
        
        for part in score.parts:
            notes = []
            for note_or_chord in part.recurse().getElementsByClass(['Note', 'Chord']):
                duration = note_or_chord.quarterLength
                if isinstance(note_or_chord, note.Note):
                    notes.append((note_or_chord.pitch.midi, duration))
                elif isinstance(note_or_chord, chord.Chord):
                    # For chords, consider both outer voices
                    pitches = sorted([n.midi for n in note_or_chord.pitches])
                    if len(pitches) > 1:
                        notes.extend([
                            (pitches[0], duration),  # Bass
                            (pitches[-1], duration)  # Soprano
                        ])
            
            # Create pairs with duration context
            for i in range(len(notes) - 1):
                voice_pairs.append((notes[i][0], notes[i+1][0], notes[i][1]))
                
        return voice_pairs

    def check_voice_leading(self, voice_pairs: List[Tuple[int, int, float]]) -> List[str]:
        s = Solver()
        
        formula_str = "Voice Leading Formula:\n"
    
        constraint_data = []
        
        for i, (note1, note2, duration) in enumerate(voice_pairs):
            # Note pair
            n1 = Int(f"note_{i}_1")
            n2 = Int(f"note_{i}_2")
            
            # Add constraints
            s.add(n1 == note1)
            s.add(n2 == note2)
            
            # Calculate the interval between notes
            interval_var = Int(f"interval_{i}")
            s.add(interval_var == Abs(n2 - n1))
            
            constraint_name = f"voice_leading_{i}"
            leap_constraint = Bool(constraint_name)
            
            # Define legal interval
            if duration >= 1.0:
                acceptable_intervals = Or(
                    interval_var <= 12,  
                    interval_var == 19, 
                    And(interval_var == 24, self.is_arpeggiation_context(note1, note2))  # Two octaves in arpeggios
                )
            else:
                acceptable_intervals = Or(
                    interval_var <= 24,
                    interval_var == 31, 
                    self.is_dramatic_gesture_formula(interval_var)
                )
            
            s.add(leap_constraint == acceptable_intervals)
            
            formula_str += f"  {constraint_name} := {leap_constraint} == {acceptable_intervals}\n"
            formula_str += f"  Where note_{i}_1 = {note1}, note_{i}_2 = {note2}, interval_{i} = {abs(note2 - note1)}\n\n"
            
            constraint_data.append((constraint_name, leap_constraint, note1, note2, interval_var))
        
        print(formula_str)
        print(f"Full SMT Formula:\n{s}")
        
        check_result = s.check()
        print(f"Satisfiability result: {check_result}")
        
        violations = []
        if check_result == unsat:

            for name, constraint, note1, note2, interval_var in constraint_data:
                # Create a separate solver for each constraint
                test_solver = Solver()
                idx = name.split('_')[-1]
                n1 = Int(f"note_{idx}_1")
                n2 = Int(f"note_{idx}_2")
                test_solver.add(n1 == note1)
                test_solver.add(n2 == note2)
                test_solver.add(interval_var == Abs(n2 - n1))
                
                test_solver.add(Not(constraint))
                if test_solver.check() == sat:
                    # This constraint is violated
                    actual_interval = abs(note2 - note1)
                    violations.append(f"Unusual leap ({actual_interval} semitones) at position {idx}")
        
        return violations
        
    def is_arpeggiation_context(self, note1: int, note2: int) -> bool:
        interval = abs(note2 - note1)
        common_arpeggio_intervals = {12, 19, 24}
        return interval in common_arpeggio_intervals
        
    def is_dramatic_gesture_formula(self, interval_var):
        # Define the dramatic intervals Mozart sometimes uses
        return Or(
            interval_var == 29,
            interval_var == 31,
            interval_var == 36,
            interval_var == 41
        )

    def check_harmony(self, score: stream.Score) -> List[str]:
        key = score.analyze('key')
        tonic_pc = key.tonic.midi % 12
        violations = []
        
        s = Solver()
        
        formula_str = "Harmony Formula:\n"
        
        # Get vertical sonorities (chords)
        chords = []
        for measure in score.recurse().getElementsByClass('Measure'):
            for chord_event in measure.getElementsByClass(['Chord']):
                pcs = {p.midi % 12 for p in chord_event.pitches}
                if pcs:
                    chords.append(pcs)
        
        constraint_data = []
        
        for i, chord_pcs in enumerate(chords):
            if len(chord_pcs) < 3:
                continue  # Skip analysis for intervals (need at least 3 notes for a chord)
                
            # Create a named constraint for this chord
            constraint_name = f"harmony_{i}"
            harmony_constraint = Bool(constraint_name)
            
            # Create variables for each pitch class in the chord
            chord_vars = []
            for j, pc in enumerate(chord_pcs):
                pc_var = Int(f"chord_{i}_pc_{j}")
                s.add(pc_var == pc)
                chord_vars.append(pc_var)
            
            # Check for harsh dissonances
            harsh_dissonance = False
            for a_idx, a in enumerate(chord_vars):
                for b_idx, b in enumerate(chord_vars):
                    if a_idx < b_idx:  # Avoid duplicate pairs
                        interval_var = Int(f"interval_{i}_{a_idx}_{b_idx}")
                        s.add(interval_var == (b - a) % 12)
                        
                        # Check for combination of harsh intervals
                        if interval_var == 1 and interval_var == 6 and interval_var == 10:
                            harsh_dissonance = True
            
            s.add(harmony_constraint == Not(harsh_dissonance))
            
            formula_str += f"  {constraint_name} := {harmony_constraint} == Not({harsh_dissonance})\n"
            formula_str += f"  Where chord_{i} = {chord_pcs}\n\n"
            
            constraint_data.append((constraint_name, harmony_constraint, i))
        
        # Print the full formula
        print(formula_str)
        print(f"Full Harmony SMT Formula:\n{s}")
        
        # Check if all constraints are satisfied
        check_result = s.check()
        print(f"Harmony satisfiability result: {check_result}")
        
        if check_result == unsat:
            # Find which constraints are violated
            for name, constraint, measure_idx in constraint_data:
                test_solver = Solver()
                test_solver.add(Not(constraint))
                if test_solver.check() == sat:
                    violations.append(f"Highly unusual dissonance in measure {measure_idx}")
        
        return violations

    def verify_piece(self, score: stream.Score) -> Tuple[bool, List[str]]:
        violations = []
        
        try:
            # Extract voice pairs with duration context
            voice_pairs = self.extract_voice_pairs(score)
            
            # Check voice leading using SMT
            voice_leading_violations = self.check_voice_leading(voice_pairs)
            violations.extend(voice_leading_violations)
            
            # Check harmony using SMT
            harmonic_violations = self.check_harmony(score)
            violations.extend(harmonic_violations)
            
            # Mozart-specific threshold: allow more expressive freedom
            violation_threshold = 3
            
            return len(violations) <= violation_threshold, violations
            
        except Exception as e:
            return False, [f"Analysis error: {str(e)}"]

def analyze_mozart_works(folder_path: str, output_file: str = "mozart_analysis_results.json"):
    checker = MozartChecker()
    results = {
        "timestamp": datetime.now().isoformat(),
        "total_files": 0,
        "valid_files": 0,
        "files_with_violations": 0,
        "analyses": []
    }
    
    print("\nMOZART STYLE ANALYSIS")
    print("=" * 50)
    
    xml_files = list(Path(folder_path).glob("*.xml")) + \
                list(Path(folder_path).glob("*.mxl")) + \
                list(Path(folder_path).glob("*.musicxml"))
    
    results["total_files"] = len(xml_files)
    print(f"\nFound {len(xml_files)} files in {folder_path}")
    
    for xml_file in xml_files:
        try:
            print(f"\nAnalyzing {xml_file.name}...")
            score = converter.parse(str(xml_file))
            
            key = score.analyze('key')
            time_sigs = score.getTimeSignatures()
            time_sig = time_sigs[0] if time_sigs else None
            
            is_valid, violations = checker.verify_piece(score)
            
            analysis = {
                "filename": xml_file.name,
                "key": str(key),
                "time_signature": str(time_sig),
                "measures": len(list(score.recurse().getElementsByClass('Measure'))),
                "valid": is_valid,
                "violations": violations
            }
            
            if is_valid:
                results["valid_files"] += 1
            else:
                results["files_with_violations"] += 1
            
            results["analyses"].append(analysis)
            
            print(f"Key: {key}")
            print(f"Time Signature: {time_sig}")
            print(f"Measures: {analysis['measures']}")
            if violations:
                print("⚠️ Potential style deviations found:")
                for v in violations:
                    print(f"  - {v}")
            else:
                print("✓ Consistent with Mozart's style")
            
        except Exception as e:
            print(f"Error analyzing {xml_file.name}: {str(e)}")
            results["analyses"].append({
                "filename": xml_file.name,
                "error": str(e)
            })
    
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_file}")
    
    print("\nANALYSIS SUMMARY")
    print("=" * 50)
    print(f"Total files analyzed: {results['total_files']}")
    print(f"Files consistent with Mozart's style: {results['valid_files']}")
    print(f"Files with style deviations: {results['files_with_violations']}")
    
    if results["total_files"] > 0:
        conformance = (results["valid_files"] / results["total_files"]) * 100
        print(f"\nOverall style conformance: {conformance:.1f}%")

if __name__ == "__main__":
    folder_path = "example"
    analyze_mozart_works(folder_path)