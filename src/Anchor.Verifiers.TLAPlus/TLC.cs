namespace Anchor.Verifiers.TLAPlus;

using sun.misc;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

using static Result;

public class TLC : Runtime
{
    public static Result<string> Check(string file, string? config = null)
    {
        if (!File.Exists(file))
        {
            return Failure<string>($"The file {file} could not be found.");
        }
        var tlc = new tlc2.TLC();
        var output = new StringWriter();
        util.SimpleFilenameToStream fts = new util.SimpleFilenameToStream(Directory.GetParent(file)?.FullName);
        string[] args = ["-fpbits", "0", "-fpmem", "1000000", "-workers", "1", Path.GetFullPath(file)];
        if (config != null)
        {
            args = new string[] { "-config", Path.GetFullPath(config) }.Concat(args).ToArray();
        }
        if (!tlc.handleParameters(args))
        {
            return Failure<string>($"The TLC checker could not handle parameters {args.JoinWith(" ")}");
        }
        //tlc2.module.TLC.OUTPUT = new java.io.BufferedWriter(new JavaStringWriter(output));
        //util.ToolIO.setUserDir(Directory.GetParent(file)?.FullName);
        //tlc2.tool.distributed.fp.FPSetManager.
        tlc.setResolver(fts);
        util.MailSender ms = new util.MailSender();
        ms.setModelName(tlc.getModelName());
        ms.setSpecName(tlc.getSpecName());
       
        try
        {
            tlc.process();
            return Success(output.ToString());
        }
        catch (Exception e)
        {            
            return Failure<string>($"Check failed. {e.Message} \n" + output.ToString());            
        }
       
    }
}
