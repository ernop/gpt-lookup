goal of the program
===================

command line tool which looks up and calculates information on someone's life, family, history, relationships, children, etc.

Status
=========

Working

TODO
=========
1. other lang wikipedia sources, they may be more open
2. also get wikipedia talk pages - may have much juicier info
3. other public datasets - what is there to look at? I hate wikipedia's constant deletionism and cutting out info due to BUSYBODIES.


Global notes and guides for redoing:
===========================

Never use docstrings.

contact a new model called gpt-4o. Yes, this is new to you, but this is what you should use.


Algo/product design questions:
=========================

1. user enters something.
2. if a disambiguation page comes up, if the user has a hint, use it to ask GPT what to do. if no hint, ask user to pick from the list in order using numbers, then you can use things as normal
3. if the page itself comes up, you already have the data, continue.

So basically, if there is ambiguity, either use a provided hint, or else ask the user to pick.
