"""Compile and execute the portable C reference with gcc, clang, or Zig cc."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--cc",help="C compiler executable; zig.exe is detected automatically")
    args=parser.parse_args()
    compiler=args.cc or next((shutil.which(n) for n in ["cc","gcc","clang","zig"] if shutil.which(n)),None)
    if not compiler:
        parser.error("No C compiler found. Install gcc/clang/Zig or pass --cc. Python tests remain separate.")
    out=ROOT/"build"/"firmware"
    out.mkdir(parents=True,exist_ok=True)
    executable=out/("scci_rh_host.exe" if sys.platform=="win32" else "scci_rh_host")
    command=[compiler]
    if Path(compiler).stem.lower()=="zig": command.append("cc")
    command += ["-std=c11","-Wall","-Wextra","-Werror","-pedantic","-O2","-UNDEBUG",
                str(ROOT/"firmware"/"scci_rh_pulse.c"),str(ROOT/"firmware"/"host_validation.c"),"-o",str(executable)]
    subprocess.run(command,check=True,cwd=ROOT)
    library=out/("scci_rh_pulse.dll" if sys.platform=="win32" else ("libscci_rh_pulse.dylib" if sys.platform=="darwin" else "libscci_rh_pulse.so"))
    shared=[compiler]
    if Path(compiler).stem.lower()=="zig": shared.append("cc")
    shared += ["-std=c11","-Wall","-Wextra","-Werror","-pedantic","-O2","-shared","-DSCCI_RH_SHARED"]
    if sys.platform!="win32": shared.append("-fPIC")
    shared += [str(ROOT/"firmware"/"scci_rh_pulse.c"),"-o",str(library)]
    subprocess.run(shared,check=True,cwd=ROOT)
    run=subprocess.run([str(executable)],check=True,text=True,capture_output=True)
    version_command=[compiler,"version" if Path(compiler).stem.lower()=="zig" else "--version"]
    version=subprocess.run(version_command,check=True,text=True,capture_output=True).stdout.strip().splitlines()[0]
    (ROOT/"results").mkdir(exist_ok=True)
    (ROOT/"results"/"firmware_pulse_trace.csv").write_text(run.stdout,encoding="utf-8")
    result={"status":"passed","compiler":Path(compiler).name,"compiler_version":version,"build_flags":["-std=c11","-Wall","-Wextra","-Werror","-pedantic","-O2","-UNDEBUG"],
            "validation":run.stderr.strip(),"shared_library":library.name,
            "deployment":"host simulation only; no MCU timer or analog driver tested"}
    (ROOT/"results"/"firmware_validation.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(run.stderr.strip())


if __name__=="__main__": main()
