import ast

tree = ast.parse(open("main.py").read())
# Drop bot.run so importing the helpers does not connect.
source = open("main.py").read().split("bot = SummaryBot()")[0]
ns = {}
exec(source, ns)
ask = ns["mention_asks_for_summary"]
assert ask("<@123> summarize") == 30
assert ask("<@123> summarise this") == 30
assert ask("<@123> summary") == 30
assert ask("<@123> tl;dr") == 30
assert ask("<@123> tldr") == 30
assert ask("<@123> recap 50") == 50
assert ask("<@123> summarize 200") == 100
assert ask("<@123> hello") is None
assert ask("<@123> summarization please") == 30
print("ok")
