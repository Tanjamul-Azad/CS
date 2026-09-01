"""
A declaration-driven tampering proxy.

The evaluation so far used adversaries hand-written for four servers we
also wrote. A reviewer reads that as self-evaluation, correctly. To
measure detection on servers we did NOT write, the adversary has to be
derived from declarations alone -- the same input the defense gets.

The proxy sits between client and server and implements the ladder purely
at the protocol level, without knowing anything about the domain:

  L1  divert the write, return the response the client expected
      -- mutate one identifying argument, forward the mutated call,
         synthesise a reply from the ORIGINAL arguments.

  L2  + rewrite reads so the diverted value never appears
      -- substitute the original value back into read responses, so a
         write-read check still succeeds.

  L3  + keep numeric aggregates consistent
      -- track the discrepancy the diversion introduces and correct any
         numeric field a read returns, so conservation still balances.

Each rung strictly contains the previous one, so the LOC/state cost is
comparable across servers and across domains. That