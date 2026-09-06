"""API-v1 bridge for an existing BOMJobPython 0.2.7 directory.

Business files bomjob.py, bom_core.py, *.ots and bomjob.ini stay in that plugin.
"""
def main(ctx):
    import bomjob
    args=[str(ctx.exchange_path),'--config',str(ctx.plugin_dir/'bomjob.ini'),'--pause','never']
    return bomjob.main(args)
