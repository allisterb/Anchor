namespace Anchor.MCPServer;

using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Linq;

using ModelContextProtocol.Server;

/// <summary>
/// Reading the knowledge base as tools, for a host that does not surface MCP resources.
/// </summary>
/// <remarks>
/// The same articles are registered as resources in <see cref="KnowledgeBase.Resources"/>. Both,
/// deliberately: resources are the natural fit and some hosts never show them, and a reference an
/// agent cannot reach is a reference that does not exist.
/// </remarks>
[McpServerToolType]
public class KnowledgeTools
{
    #region Methods

    [McpServerTool(Name = "ListKnowledge")]
    [Description(
        "Lists Anchor's knowledge-base articles — short reference pages on how to use these tools " +
        "and, more importantly, on what their answers do and do not establish.\n\n" +
        "Read the relevant one BEFORE reporting a verdict to a user. The tool descriptions carry " +
        "the rules; these carry the reasoning, which is what stops a bounded answer being repeated " +
        "as a proof. Cheap: no model checking, no subprocess.\n\n" +
        "Start with `reading-verdicts` if you have a result in hand, `the-modelled-subset` if a " +
        "call was REFUSED, and `writing-a-property-module` before using CheckPolicy's `property`.")]
    public static IReadOnlyList<ArticleSummary> ListKnowledge(
        [Description("Optional case-insensitive substring. Matches name, title, description and body. Omit to list everything — there are only a handful.")] string? search = null)
        => [.. KnowledgeBase.Search(search).Select(a => a.Summary)];

    [McpServerTool(Name = "ReadKnowledge")]
    [Description(
        "Returns one knowledge-base article in full, by name (as given by ListKnowledge; the " +
        "`.md` suffix is optional). Ask for several by passing several names.")]
    public static IReadOnlyList<ArticleContent> ReadKnowledge(
        [Description("Article names, e.g. ['reading-verdicts'].")] string[] names)
    {
        if (names is null || names.Length == 0)
        {
            throw new ArgumentException(
                "Name at least one article. Call ListKnowledge to see what is available.", nameof(names));
        }

        // Validated one at a time so a bad name names itself, rather than the whole call failing
        // with a message about some other article.
        return [.. names.Select(n =>
        {
            var article = KnowledgeBase.Find(n);
            return article is null
                ? new ArticleContent(n, "", "", $"No article called '{n}'. Call ListKnowledge for the available names.")
                : new ArticleContent(article.Name, article.Title, KnowledgeBase.Uri(article.Name), article.Content);
        })];
    }

    #endregion
}

/// <summary>One article's full text.</summary>
public record ArticleContent(string Name, string Title, string Uri, string Content);
