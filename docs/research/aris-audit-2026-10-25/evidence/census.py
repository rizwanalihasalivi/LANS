import ast,collections,csv,gzip,json,math,subprocess,zipfile
from pathlib import Path
root=Path('/workspace/LANS');out=Path('/workspace/lans-aris-audit')
files=[root/p for p in subprocess.check_output(['git','ls-files','-z'],cwd=root,text=True).split('\0') if p]
stats=collections.Counter();errors=[];records=[];unique={};metric_checks=[]
for p in files:
    rel=str(p.relative_to(root)); ext=p.suffix.lower();stats['files']+=1
    r={'path':rel,'extension':ext,'bytes':p.stat().st_size,'checks':[]}
    try:
        if ext=='.py':
            data=p.read_bytes();ast.parse(data,filename=rel);r['checks'].append('python_ast_parse')
            key=unique.setdefault(data,[]);key.append(rel);stats['python_files']+=1
        if ext=='.json':
            data=json.loads(p.read_text());r['checks'].append('json_parse');stats['json_files']+=1
        if ext=='.csv' or p.name.endswith('.csv.gz'):
            op=gzip.open if ext=='.gz' else open
            with op(p,'rt',newline='') as s:
                reader=csv.reader(s);count=0;widths=collections.Counter()
                for row in reader:count+=1;widths[len(row)]+=1
            r.update(rows=count,widths=dict(widths));r['checks'].append('csv_full_stream_parse');stats['csv_files']+=1;stats['csv_rows']+=count
        if ext=='.zip' or ext=='.docx':
            with zipfile.ZipFile(p) as z:
                bad=z.testzip();r['members']=len(z.infolist());r['member_bytes']=sum(i.file_size for i in z.infolist())
                if bad:raise ValueError('ZIP CRC mismatch: '+bad)
            r['checks'].append('zip_all_member_crc');stats['archive_files']+=1
        if ext=='.log':
            data=p.read_text(errors='replace');r['lines']=len(data.splitlines());r['traceback_count']=data.count('Traceback (most recent call last)');r['checks'].append('log_stream_and_traceback_count');stats['logs']+=1
    except Exception as e:
        r['error']=str(e);errors.append({'path':rel,'error':str(e)})
    records.append(r)
for p in root.glob('integrations/webots/results/**/metrics.json'):
    tp=p.parent/'telemetry.csv'
    if not tp.exists():continue
    d=json.loads(p.read_text());rows=list(csv.DictReader(tp.open()));check={'path':str(p.relative_to(root)),'samples':len(rows),'mismatches':[]}
    if rows and 'error_m' in rows[0]:
        ss=sum(float(r['error_m'])**2 for r in rows);rmse=math.sqrt(ss/len(rows))
        for key,val in [('rmse_m',rmse),('max_abs_error_m',max(abs(float(r['error_m'])) for r in rows)),('steps',len(rows))]:
            if key in d and not math.isclose(float(d[key]),val,rel_tol=1e-10,abs_tol=1e-10):check['mismatches'].append([key,d[key],val])
        if 'penalized_rmse_m' in d:
            scheduled=d['scheduled_steps'];value=math.sqrt((ss+(scheduled-len(rows))*6.25)/scheduled)
            if not math.isclose(d['penalized_rmse_m'],value,rel_tol=1e-10,abs_tol=1e-10):check['mismatches'].append(['penalized_rmse_m',d['penalized_rmse_m'],value])
        if 'reference_y_m' in rows[0] and 'y_cg_m' in rows[0]:
            check['max_reference_error_identity_gap']=max(abs(float(r['error_m'])-(float(r['y_cg_m'])-float(r['reference_y_m']))) for r in rows)
    metric_checks.append(check)
stats['unique_python_contents']=len(unique);stats['native_metrics_recomputed']=len(metric_checks)
(out/'census-details.json').write_text(json.dumps(records,indent=2)+'\n')
(out/'source-duplicates.json').write_text(json.dumps(list(unique.values()),indent=2)+'\n')
(out/'native-metric-checks.json').write_text(json.dumps(metric_checks,indent=2)+'\n')
summary={'counts':dict(stats),'parse_errors':errors,'native_metric_mismatches':[m for m in metric_checks if m['mismatches']]}
(out/'census-summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
