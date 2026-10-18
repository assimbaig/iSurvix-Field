"""Package only approved end-user documentation; never include internal files."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT=Path(__file__).resolve().parents[1]
FILES=[ROOT/'docs/manual'/f'iSurvix_Field_Software_Manual.{ext}' for ext in ('pdf','docx')]

def main():
    for source in FILES:
        if not source.is_file():
            raise SystemExit(f'Missing end-user manual: {source.name}')
    output=ROOT/'.local/release-documentation/iSurvix_Field_User_Documentation.zip'
    output.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(output,'w',ZIP_DEFLATED) as archive:
        for source in FILES:
            archive.write(source,source.name)
    print(output)

if __name__=='__main__':
    main()
