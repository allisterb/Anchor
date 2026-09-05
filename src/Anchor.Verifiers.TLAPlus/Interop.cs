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


/// <summary>
/// A java.io.Writer-compatible implementation that wraps a .NET StringWriter.
/// Designed for IKVM/java interop code that expects a java.io.Writer backed by a string buffer.
/// </summary>
internal sealed class JavaStringWriter : java.io.Writer
{
    private readonly StringWriter writer;
    private bool closed;

    public JavaStringWriter()
        : this(new StringWriter())
    {
    }

    public JavaStringWriter(StringWriter writer)
    {
        this.writer = writer ?? throw new java.lang.NullPointerException();
        closed = false;
    }

    // Expose the underlying StringWriter for reading the accumulated contents.
    public StringWriter UnderlyingWriter => writer;

    public override void write(int c)
    {
        lock (this)
        {
            ensureOpen();
            writer.Write((char)c);
        }
    }

    public override void write(char[] cbuf, int off, int len)
    {
        if (cbuf is null) throw new java.lang.NullPointerException();
        if (off < 0 || len < 0 || off + len > cbuf.Length) throw new java.lang.ArrayIndexOutOfBoundsException();

        lock (this)
        {
            ensureOpen();
            writer.Write(cbuf, off, len);
        }
    }

    public override void write(string str, int off, int len)
    {
        if (str is null) throw new java.lang.NullPointerException();
        if (off < 0 || len < 0 || off + len > str.Length) throw new java.lang.StringIndexOutOfBoundsException();

        lock (this)
        {
            ensureOpen();
            writer.Write(str.Substring(off, len));
        }
    }

    public override void flush()
    {
        lock (this)
        {
            ensureOpen();
            writer.Flush();
        }
    }

    public override void close()
    {
        lock (this)
        {
            if (closed) return;
            writer.Close();
            closed = true;
        }
    }

    private void ensureOpen()
    {
        if (closed) throw new java.io.IOException("Writer closed");
    }

    public string AsString() => writer.ToString();
}