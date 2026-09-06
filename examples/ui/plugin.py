"""Small UI example: an explicit Apply edits title-block text below its heading.

Not a replacement for the existing TitleJob UI/VPT editor.
"""
import tkinter as tk
from tkinter import messagebox
import xml.etree.ElementTree as ET

def main(ctx):
    document=ctx.document()
    values=ctx.environment(['author'])
    root=tk.Tk();root.title('DipTrace adapter: title field demo')
    tk.Label(root,text='Designed by / author').pack(padx=20,pady=10)
    entry=tk.Entry(root,width=45);entry.pack(padx=20,pady=10)
    entry.insert(0,values.get('author',''))
    def apply():
        count=0
        for field in document.findall('./Schematic/SheetSettings/Sheets/Sheet/BorderZones/*/Fields/Field'):
            if field.get('TextShow','Text')!='Text':continue
            lines=field.find('TextLines')
            if lines is None or not len(lines):continue
            heading=(lines[0].text or '').splitlines()
            if not heading or heading[0]!='Designed by':continue
            lines[0].text=heading[0]
            for child in list(lines)[1:]:lines.remove(child)
            # The heading remains; all later lines are replaced.
            ET.SubElement(lines,'TextLine').text=entry.get()
            count+=1
        if not count:messagebox.showwarning('No matching field','Designed by was not found.');return
        try:ctx.commit_xml(document)
        except Exception as e:messagebox.showerror('Not applied',str(e));return
        root.destroy()
    def cancel():ctx.cancel();root.destroy()
    tk.Button(root,text='Apply to active project',command=apply).pack(pady=10)
    tk.Button(root,text='Cancel',command=cancel).pack(pady=10)
    root.protocol('WM_DELETE_WINDOW',cancel)
    root.mainloop()
