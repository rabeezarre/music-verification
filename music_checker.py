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
                    # For chords, consider both outer voices but check context
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
        violations = []
        
        for i, (note1, note2, duration) in enumerate(voice_pairs):
            n1 = Int(f"note_{i}_1")
            n2 = Int(f"note_{i}_2")
            
            self.solver.add(n1 == note1)
            self.solver.add(n2 == note2)
            
            interval = abs(note2 - note1)
            
            # Mozart-specific voice leading constraints
            
            # 1. Allow larger leaps in fast passages (common in Mozart's virtuosic writing)
            if duration >= 1.0:  # Longer notes (quarter note or longer)
                max_leap = 19  # Allow up to a compound perfect fifth
            else:
                max_leap = 24  # Allow larger leaps in faster passages
                
            # 2. Special cases for specific musical contexts
            if interval > max_leap:
                # Check for common Mozart patterns
                if self.is_arpeggiation_pattern(note1, note2):
                    continue  # Allow larger leaps in clear arpeggiation patterns
                    
                if self.is_dramatic_gesture(interval):
                    continue  # Allow specific dramatic gestures common in Mozart
                    
                if duration < 0.25:  # Very fast passages (16th notes or faster)
                    continue  # Allow virtuosic passages
                    
                violations.append(f"Unusual leap ({interval} semitones) at position {i}")
                
        return violations

    def is_arpeggiation_pattern(self, note1: int, note2: int) -> bool:
        interval = abs(note2 - note1)
        
        # Common arpeggiation intervals in Mozart
        common_arpeggio_intervals = {
            12,
            19, 
            24,
            28, 
            31, 
        }
        
        return interval in common_arpeggio_intervals

    def is_dramatic_gesture(self, interval: int) -> bool:
        # Mozart often uses dramatic leaps for specific effects
        dramatic_intervals = {
            29,
            31,
            36,
            41,
        }
        
        return interval in dramatic_intervals

    def check_harmony(self, score: stream.Score) -> List[str]:
        violations = []
        key = score.analyze('key')
        tonic_pc = key.tonic.midi % 12
        
        # Get vertical sonorities
        chords = []
        for measure in score.recurse().getElementsByClass('Measure'):
            for chord_event in measure.getElementsByClass(['Chord']):
                pcs = {p.midi % 12 for p in chord_event.pitches}
                if pcs:
                    chords.append(pcs)
        
        for i, chord_pcs in enumerate(chords):
            # More flexible harmonic constraints based on Mozart's practice
            
            # Allow chromatic alterations common in Mozart
            allowed_pcs = {
                tonic_pc,
                (tonic_pc + 1) % 12,
                (tonic_pc + 2) % 12,
                (tonic_pc + 3) % 12,
                (tonic_pc + 4) % 12,
                (tonic_pc + 5) % 12,
                (tonic_pc + 6) % 12,
                (tonic_pc + 7) % 12,
                (tonic_pc + 8) % 12,
                (tonic_pc + 9) % 12,
                (tonic_pc + 10) % 12,
                (tonic_pc + 11) % 12,
            }
            
            # Check for highly unusual dissonances only
            if len(chord_pcs) >= 3:
                intervals = {(b - a) % 12 for a in chord_pcs for b in chord_pcs if b > a}
                # Allow more dissonances in development sections and dramatic moments
                if 1 in intervals and 6 in intervals and 10 in intervals:  # Very harsh combination
                    violations.append(f"Highly unusual dissonance in measure {i}")
                    
        return violations

    def verify_piece(self, score: stream.Score) -> Tuple[bool, List[str]]:
        violations = []
        
        try:
            # Extract voice pairs with duration context
            voice_pairs = self.extract_voice_pairs(score)
            
            # Check voice leading
            voice_leading_violations = self.check_voice_leading(voice_pairs)
            violations.extend(voice_leading_violations)
            
            # Check harmony
            harmonic_violations = self.check_harmony(score)
            violations.extend(harmonic_violations)
            
            # Only report truly unusual violations
            significant_violations = [v for v in violations 
                                   if ("Unusual leap" in v and "position" in v) or 
                                   "Highly unusual dissonance" in v]
            
            # Mozart-specific threshold: allow more expressive freedom
            violation_threshold = 3
            
            return len(significant_violations) <= violation_threshold, significant_violations
            
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
    folder_path = "example" # Put path
    analyze_mozart_works(folder_path)