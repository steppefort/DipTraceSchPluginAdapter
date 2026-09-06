"""Read-only job example. No BOM/TitleJob rules in the shared adapter."""
import json

def main(ctx):
    root=ctx.document()
    values=ctx.environment(['projectname','revision'])
    ctx.log('Read project; no changes returned to DipTrace')
    # Example output stays inside diagnostics, never an assumed project path.
    (ctx.run_dir/'summary.json').write_text(json.dumps({
        'source_type':root.get('Type'),'project_dir':str(ctx.project_dir),
        'variables':values},ensure_ascii=False,indent=2),encoding='utf-8')
