using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Anchor
{
    public static class StringExtensions
    {
        public static string Delete(this string s, string r) => s.Replace(r, string.Empty);

        public static string JoinSuperscript(this string s, string r)
        {
            if (s.Contains("_"))
            {
                return s.Insert(s.IndexOf("_") + 1, "{") + s + r + "}";
            }
            else
            {
                return s + "_" + r;
            }
        }

        public static string JoinWith(this IEnumerable<string> s, string sep) => s.Aggregate((l, r) => l + sep + r);

        public static string JoinWithNewlines(this IEnumerable<string> s) => s.JoinWith(Environment.NewLine);
    }
}
