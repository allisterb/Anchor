namespace Anchor.Verifiers.TLAPlus;

using System;
using System.Collections.Generic;
using System.Text;

internal sealed class StringBuilderOutputStream : java.io.OutputStream
{
    private readonly StringBuilder sb;
    private readonly Encoding encoding;

    public StringBuilderOutputStream(StringBuilder sb, System.Text.Encoding? encoding = null)
    {
        this.sb = sb ?? throw new ArgumentNullException(nameof(sb));
        this.encoding = encoding ?? System.Text.Encoding.UTF8;
    }

    // Write a single byte
    public override void write(int b)
    {
        var ch = (byte)(b & 0xFF);
        sb.Append(this.encoding.GetString(new byte[] { ch }));
    }

    // Write a byte array slice
    public override void write(byte[] b, int off, int len)
    {
        if (b is null) throw new java.lang.NullPointerException();
        if (off < 0 || len < 0 || off + len > b.Length) throw new java.lang.ArrayIndexOutOfBoundsException();
        if (len == 0) return;
        var bytes = new byte[len];
        Array.Copy(b, off, bytes, 0, len);
        sb.Append(this.encoding.GetString(bytes));
    }

    public override void write(byte[] b)
    {
        if (b is null) throw new java.lang.NullPointerException();
        write(b, 0, b.Length);
    }

    public override void flush() { }

    public override void close() { }
}
