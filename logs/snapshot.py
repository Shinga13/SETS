import sys, platform
python_version = sys.version
python_version = python_version.replace('\r', '')
python_version = python_version.replace('\n', '')
system = platform.system()
release = platform.release()

try:
    build = sys.getwindowsversion().build
    if system == 'Windows' and release == 10 and build >= 22000:
        release = 11
except:
    build = ''

try:
    import tkinter as tk
    tkinter_version = tk.Tcl().call("info", "patchlevel")
    root = tk.Tk()
    tk_screen_geometry = '{}x{}'.format(root.winfo_screenwidth(), root.winfo_screenheight())
    dpi = round(root.winfo_fpixels('1i'), 0)
    factor = (dpi / 96)
except:
    tkinter_version = 'fail'
    tk_screen_geometry = 'fail'
    dpi = ''
    factor = ''

try:
    import csv
    release_data = dict()
    with open('/etc/os-release') as f:
        os_release = csv.reader(f, delimiter='=')
        for row in os_release:
            release_data[row[0]] = row[1]
        distribution = '{} {}'.format(release_data['NAME'], release_data['VERSION'])
except:
    distribution = ''

os_text = '{} {}'.format(system, release)
if build:
    os_text += ' ({})'.format(build)
if distribution:
    os_text += ' ({})'.format(distribution)

try:
    import PIL
    PIL_version = PIL.__version__
except:
    PIL_version = 'fail'

try:
    import numpy
    numpy_version = numpy.__version__
except:
    numpy_version = 'fail'

snapshot = {
    'python': python_version,
    'OS': os_text,
    'screen-dpi': '{} ({}dpi x{})'.format(tk_screen_geometry, dpi, factor),
}

modules= {
    'tkinter': tkinter_version,
    'Pillow': PIL_version,
    'numpy': numpy_version,
}

min_title_width = 5
for type in snapshot:
    if len(type) > min_title_width:
        min_title_width = len(type)

for type in snapshot:
    print('{:>{min}}: {}'.format(type, snapshot[type], min=min_title_width+1))

modules_text = '{:>{min}}: '.format('modules', min=min_title_width+1)

for type in modules:
    modules_text += '({} {}) '.format(type, modules[type])

print(modules_text)
