---- MODULE ProducerConsumerQueue ----
EXTENDS Integers, Sequences, FiniteSets, TLC

CONSTANTS K, NULL

VARIABLES head, tail, buffer

====
