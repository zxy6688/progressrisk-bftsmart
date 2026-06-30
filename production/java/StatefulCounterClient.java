package progressrisk.bftsmart;

import bftsmart.tom.ServiceProxy;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;

/**
 * Closed-loop client for the A1 stateful baseline. Every accepted reply is
 * checked against the exact expected counter value and logged as a sentinel.
 */
public final class StatefulCounterClient {
    private StatefulCounterClient() {
    }

    private static byte[] command(int increment) throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream(4);
        DataOutputStream out = new DataOutputStream(bytes);
        out.writeInt(increment);
        out.flush();
        return bytes.toByteArray();
    }

    private static int decode(byte[] reply) throws IOException {
        if (reply == null || reply.length != 4) {
            throw new IOException("invalid reply length: " + (reply == null ? -1 : reply.length));
        }
        return new DataInputStream(new ByteArrayInputStream(reply)).readInt();
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 3) {
            System.err.println("Usage: StatefulCounterClient <client-id> <increment> <operations>");
            System.exit(2);
        }

        int clientId = Integer.parseInt(args[0]);
        int increment = Integer.parseInt(args[1]);
        int requestedOperations = Integer.parseInt(args[2]);
        if (requestedOperations < 1) {
            throw new IllegalArgumentException("operations must be >= 1");
        }

        try (ServiceProxy proxy = new ServiceProxy(clientId)) {
            for (int sequence = 1; sequence <= requestedOperations; sequence++) {
                int actual = decode(proxy.invokeOrdered(command(increment)));
                int expected = sequence * increment;
                if (actual != expected) {
                    throw new IllegalStateException(
                            "counter mismatch at sequence " + sequence + ": expected " + expected + ", got " + actual);
                }
                System.out.printf(
                        "STATEFUL_CLIENT_REPLY sequence=%d value=%d expected=%d%n",
                        sequence, actual, expected);
            }
        }
    }
}
