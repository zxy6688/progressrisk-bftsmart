package progressrisk.bftsmart;

import bftsmart.tom.ServiceProxy;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;

/**
 * A one-shot ordered client for the A2 handoff gate.
 *
 * Each invocation is deliberately a fresh process with a freshly distributed
 * currentView file. This matches BFT-SMaRt's requirement that clients started
 * after a reconfiguration use the latest view. The client validates the exact
 * counter value carried across state transfer rather than merely accepting a
 * syntactically valid reply.
 */
public final class HandoffSequenceClient {
    private HandoffSequenceClient() {
    }

    private static byte[] incrementCommand() throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream(4);
        DataOutputStream out = new DataOutputStream(bytes);
        out.writeInt(1);
        out.flush();
        return bytes.toByteArray();
    }

    private static int decodeCounter(byte[] reply) throws IOException {
        if (reply == null || reply.length != 4) {
            throw new IOException("invalid reply length: " + (reply == null ? -1 : reply.length));
        }
        return new DataInputStream(new ByteArrayInputStream(reply)).readInt();
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 4) {
            System.err.println("Usage: HandoffSequenceClient <client-id> <expected-first-value> <operations> <phase>");
            System.exit(2);
        }

        int clientId = Integer.parseInt(args[0]);
        int expectedFirstValue = Integer.parseInt(args[1]);
        int operations = Integer.parseInt(args[2]);
        String phase = args[3];
        if (expectedFirstValue < 1 || operations < 1) {
            throw new IllegalArgumentException("expected-first-value and operations must be >= 1");
        }

        try (ServiceProxy proxy = new ServiceProxy(clientId)) {
            for (int sequence = 0; sequence < operations; sequence++) {
                int expected = expectedFirstValue + sequence;
                int actual = decodeCounter(proxy.invokeOrdered(incrementCommand()));
                if (actual != expected) {
                    throw new IllegalStateException(
                            "counter mismatch in " + phase + " at sequence " + (sequence + 1)
                                    + ": expected " + expected + ", got " + actual);
                }
                System.out.printf(
                        "HANDOFF_CLIENT_REPLY phase=%s sequence=%d value=%d expected=%d epoch_ms=%d%n",
                        phase, sequence + 1, actual, expected, System.currentTimeMillis());
            }
        }
    }
}
