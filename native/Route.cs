using System;
using System.Runtime.InteropServices;

class Route
{
    [DllImport("libaul.so.0")]
    static extern int aul_launch_app(string app, IntPtr data);

    static int Main()
    {
        if (IntPtr.Size != 4) return 1;
        return aul_launch_app("Q70Home001.Home", IntPtr.Zero) < 0 ? 1 : 0;
    }
}
