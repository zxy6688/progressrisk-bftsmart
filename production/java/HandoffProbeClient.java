package progressrisk.bftsmart;

import bftsmart.tom.ServiceProxy;
import java.io.BufferedWriter;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.nio.file.Files;
import java.nio.file.Path;

/** Closed-loop ordered-request probe; flushes every outcome so failures retain evidence. */
public final class HandoffProbeClient {
    private static byte[] command(int increment) throws Exception { ByteArrayOutputStream bytes = new ByteArrayOutputStream(4); try (DataOutputStream out = new DataOutputStream(bytes)) { out.writeInt(increment); out.flush(); } return bytes.toByteArray(); }
    private static long epochNs() { java.time.Instant now = java.time.Instant.now(); return now.getEpochSecond() * 1_000_000_000L + now.getNano(); }
    public static void main(String[] args) throws Exception {
        if (args.length != 5) { System.err.println("Usage: HandoffProbeClient <client-id> <increment> <duration-seconds> <output-csv> <retry-ms>"); System.exit(2); }
        int clientId = Integer.parseInt(args[0]); int increment = Integer.parseInt(args[1]); long durationNs = Long.parseLong(args[2]) * 1_000_000_000L; Path out = Path.of(args[3]); long retryMs = Long.parseLong(args[4]);
        Files.createDirectories(out.toAbsolutePath().getParent());
        try (BufferedWriter csv = Files.newBufferedWriter(out); ServiceProxy proxy = new ServiceProxy(clientId)) {
            csv.write("start_epoch_ns,end_epoch_ns,ok,error\n"); csv.flush();
            long deadline = System.nanoTime() + durationNs;
            while (System.nanoTime() < deadline) {
                long start = epochNs();
                try { byte[] reply = increment == 0 ? proxy.invokeUnordered(command(increment)) : proxy.invokeOrdered(command(increment)); long end = epochNs(); csv.write(start + "," + end + "," + (reply != null) + ",\n"); }
                catch (Exception e) { long end = epochNs(); csv.write(start + "," + end + ",false," + e.getClass().getSimpleName().replace(',', '_') + "\n"); Thread.sleep(retryMs); }
                csv.flush();
            }
        }
    }
}
