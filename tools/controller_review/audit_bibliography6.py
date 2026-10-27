"""Audit supplied manuscript entries without inventing publisher verification."""
import argparse
import json
import re
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--manuscript',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    text=a.manuscript.read_text();refs=text.split('REFERENCES\n',1)[1].split('\nTABLE 1',1)[0]
    entries=re.findall(r'^\[(\d+)\]\s+(.+)$',refs,re.M);assert len(entries)==32
    rows=[]
    for number,entry in entries:
        n=int(number);notes=[];status='Primary-source metadata verification pending'
        if n in (18,26):
            status='Replace and deduplicate using supplied Kalaria arXiv2208.13856v1'
            notes.append('Both entries appear to refer to the same work; their IV/TCST venue claims do not match the supplied TIV masthead. Use verified version-specific title including “and Racing”; do not invent final volume/DOI.')
        if n in (23,24):notes.append('Duplicate title and venue/year with different author attribution; consolidate only after original primary paper is checked.')
        if n==6:notes.append('Introduction cites this LQR book for GPU power figures; the in-text evidence mapping must be replaced or the unsupported numeric claim removed.')
        if n in (4,5):notes.append('Introduction ECU hardware/clock assertion requires an actual ECU datasheet; GPU white paper/driving survey is not sufficient primary evidence for that exact hardware claim.')
        if n in (7,8):notes.append('Do not use a generic vehicle-dynamics/model reference as evidence for neural inference WCET; require directly relevant measured/certified timing evidence.')
        rows.append(dict(original_number=n,original_entry=entry,status=status,notes=notes))
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'bibliography-audit.json').write_text(json.dumps(dict(entries=rows,all32_structurally_reviewed=True,all32_primary_verified=False,verified_supplied_source_entries=5),indent=2)+'\n')
    lines=['# Original manuscript bibliography audit','',
        'All 32 entries were structurally reviewed against the supplied manuscript. This is not a claim that all publisher metadata or cited numerical statements have been independently verified. The five uploaded PDFs support the version-specific entries in ../reviewer-aligned-v3/verified-references.md. No external publisher access or unseen primary source is invented.','',
        '| Original entry | Status and required correction |','|---|---|']
    for row in rows:lines.append(f'| [{row["original_number"]}] | '+row['status']+'. '+' '.join(row['notes'])+' |')
    lines+=['','Before submission, obtain/verify every retained primary source and rebuild in-text numbering after deduplication. Remove unsupported 49-fold speedup, GPU/CPU energy, total blind-distance, global stability and generalization claims rather than attaching unverified citations. An inference benchmark is not a control-period benchmark.','',
        'The full robust vehicle-comparator gap is also explicit: a model-error confidence construction, uncertainty-consistent constraint tightening, terminal safe set/controller, initial feasibility and solver-failure/shrinking-horizon handling are needed. The independently verified scalar Algorithm2 contract exercises those mechanisms under its own declared assumptions; it cannot transfer its guarantee to Gaussian noisy-state nonlinear LANS.']
    (a.output/'bibliography-audit.md').write_text('\n'.join(lines)+'\n');print('Reviewed32 original entries; complete publisher verification remains pending.')

if __name__=='__main__':main()
