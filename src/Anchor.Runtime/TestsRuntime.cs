namespace Anchor.Tests;

using Microsoft.Extensions.Configuration;
using System;
using System.Collections.Concurrent;
using System.IO;
using System.Net.Sockets;


public class TestsRuntime : Runtime
{
    static TestsRuntime()
    {
        Runtime.WithFileAndConsoleLogging("Anchor", "Tests", true);
        config = LoadConfigFile(Path.Combine(AssemblyLocation, "testappsettings.json"), false);
    }

    static protected new IConfigurationRoot config;  
}
