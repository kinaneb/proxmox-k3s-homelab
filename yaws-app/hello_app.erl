-module(hello_app).
-export([out/1]).

out(_Arg) ->
  {html, "<h1>Erlang is ALIVE!</h1><p>The module finally loaded.</p>"}.