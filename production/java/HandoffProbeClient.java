package progressrisk.bftsmart;

import bftsmart.tom.ServiceProxy;

import java.io.ByteArrayOutputStream;
import java.io.DataOutputStream;
import java.io.BufferedWriter;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;

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

        long deadline = System.nanoTime() + durationNs;
        try (BufferedWriter writer = Files.newBufferedWriter(
                     out, StandardOpenOption.CREATE, StandardOpenOption.TRUNCATE_EXISTING);
             ServiceProxy proxy = new ServiceProxy(clientId)) {
            writer.write("start_epoch_ns,end_epoch_ns,ok,error\n");
            writer.flush();
            while (System.nanoTime() < deadline) {
                long start = epochNs();
                try {
                    byte[] reply = increment == 0
                            ? proxy.invokeUnordered(command(increment))
                            : proxy.invokeOrdered(command(increment));
                    long end = epochNs();
                    writer.write(start + "," + end + "," + (reply != null) + ",\n");
                } catch (Exception e) {
                    long end = epochNs();
                    String type = e.getClass().getSimpleName().replace(',', '_');
                    writer.write(start + "," + end + ",false," + type + "\n");
                    Thread.sleep(retryMs);
                }
                writer.flush();
            }
        }
    }
}
