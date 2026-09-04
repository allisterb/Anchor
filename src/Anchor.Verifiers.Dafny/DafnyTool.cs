namespace Anchor.Verifiers.Dafny;

using System;
using System.IO;
using System.Threading.Tasks;

using Microsoft.Dafny;

public class DafnyTool : Runtime
{        
    public static async Task<ToolOutput> Resolve(string src)
    {        
        (var stdin, var stdout, var stderr) = ToolOutput.CreateStreams(src);
        string[] args = ["resolve", "--standard-libraries", "--stdin"];
        var r = await DafnyBackwardsCompatibleCli.MainWithWriters(stdout, stderr, stdin, args);
        return new ToolOutput(r, stdout, stderr);
    }   
}
