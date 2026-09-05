namespace Anchor.Verifiers.TLAPlus;

using System;
using System.Text;

using static Result;

public class SANY : Runtime
{
    public static Result<string> Parse(string file)
    {
        if (!File.Exists(file))
        {
            return Failure<string>($"The file {file} could not be found.");
        }
        util.SimpleFilenameToStream fts = new util.SimpleFilenameToStream(Directory.GetParent(file)?.FullName);
        var spec = new tla2sany.modanalyzer.SpecObj(Path.GetFullPath(file), fts);        
        var sb = new StringBuilder();        
        var stream = new java.io.PrintStream(new StringBuilderOutputStream(sb));        
        try
        {
            tla2sany.drivers.SANY.frontEndInitialize(spec, stream);
            tla2sany.drivers.SANY.frontEndParse(spec, stream);
            return Success(sb.ToString());
        }
        catch (Exception)
        {           
            return Failure<string>(sb.ToString());
        }
    }
}
