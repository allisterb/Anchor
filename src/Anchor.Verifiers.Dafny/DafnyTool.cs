namespace Anchor.Verifiers.Dafny;

using System;
using System.IO;
using System.Threading.Tasks;

using Microsoft.Dafny;

public class DafnyTool : Runtime
{        
    public static async Task<string> ResolveAsync(string src)
    {        
        (var stdin, var stdout, var stderr) = ToolOutput.CreateStreams(src);
        string[] args = ["resolve", "--standard-libraries", "--stdin"];
        var program = await ProgramParser.Parse(src, new Uri("file://text"), null);
        var r = DafnyMain.Resolve(program.Program);
        return r;
    }   
}
