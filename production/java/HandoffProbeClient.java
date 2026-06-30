package progressrisk.bftsmart;

import bftsmart.tom.ServiceProxy;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.nio.file.Files;
import java.nio.file.Path;

/** Closed-loop request probe emitting nanosecond timestamped client outcomes. */
public final class HandoffProbeClient {
    private static byte[] command(int increment) throws Exception {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream(4);
        new DataOutputStream(bytes).writeInt(increment);
        return bytes.toByteArray();
    }

    private static long epochNs() {
        java.time.Instant now = java.time.Instant.now();
        return now.getEpochSecond() * 1_000_000_000L + now.getNano();
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 5) {
            System.err.println("Usage: HandoffProbeClient <client-id> <increment> <duration-seconds> <output-csv> <retry-ms>");
            System.exit(2);
        }
        int clientId = Integer.parseInt(args[0]);
        int increment = Integer.parseInt(args[1]);
        long durationNs = Long.parseLong(args[2]) * 1_000_000_000L;
        Path out = Path.of(args[3]);
        long retryMs = Long.parseLong(args[4]);
        Files.createDirectories(out.toAbsolutePath().getParent());

        StringBuilder csv = new StringBuilder("start_epoch_ns,end_epoch_ns,ok,error\n");
        long deadline = System.nanoTime() + durationNs;
        try (ServiceProxy proxy = new ServiceProxy(clientId)) {
            while (System.nanoTime() < deadline) {
                long start = epochNs();
                try {
                    byte[] reply = increment == 0 ? proxy.invokeUnordered(command(increment)) : proxy.invokeOrdered(command(increment));
                    long end = epochNs();
                    csv.append(start).append(',').append(end).append(',').append(reply != null).append(",\n");
                } catch (Exception e) {
                    long end = epochNs();
                    String type = e.getClass().getSimpleName().replace(',', '_');
                    csv.append(start).append(',').append(end).append(",false,").append(type).append('\n');
                    Thread.sleep(retryMs);
                }
            }
        }
        Files.writeString(out, csv.toString());
    }
}
