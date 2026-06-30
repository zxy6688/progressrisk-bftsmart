package progressrisk.bftsmart;

import bftsmart.tom.MessageContext;
import bftsmart.tom.ServiceReplica;
import bftsmart.tom.server.defaultservices.DefaultSingleRecoverable;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;

/**
 * Stateful counter for the BFT-SMaRt handoff benchmark.
 *
 * The joining replica must invoke installSnapshot() after it has received
 * application state. The marker includes the transferred payload size and the
 * number of ordered operations already incorporated, so a zero-state join
 * cannot be mistaken for a successful state-transfer trial.
 */
public final class StatefulCounterServer extends DefaultSingleRecoverable {
    private int counter = 0;
    private int operations = 0;
    private byte[] snapshotPayload;

    public StatefulCounterServer(int id, int snapshotBytes) {
        if (snapshotBytes < 0) {
            throw new IllegalArgumentException("snapshotBytes must be nonnegative");
        }
        this.snapshotPayload = new byte[snapshotBytes];
        for (int i = 0; i < snapshotPayload.length; i++) {
            snapshotPayload[i] = (byte) (i % 251);
        }
        new ServiceReplica(id, this, this);
        System.out.printf(
                "STATEFUL_COUNTER_READY id=%d snapshot_bytes=%d payload_sha256=%s%n",
                id, snapshotBytes, sha256(snapshotPayload));
    }

    @Override
    public byte[] appExecuteUnordered(byte[] command, MessageContext context) {
        return encode(counter);
    }

    @Override
    public byte[] appExecuteOrdered(byte[] command, MessageContext context) {
        try {
            int increment = new DataInputStream(new ByteArrayInputStream(command)).readInt();
            counter += increment;
            operations += 1;
            return encode(counter);
        } catch (IOException e) {
            throw new IllegalStateException("invalid counter command", e);
        }
    }

    @Override
    public void installSnapshot(byte[] state) {
        try (ObjectInputStream in = new ObjectInputStream(new ByteArrayInputStream(state))) {
            counter = in.readInt();
            operations = in.readInt();
            int len = in.readInt();
            snapshotPayload = new byte[len];
            in.readFully(snapshotPayload);
            System.out.printf(
                    "STATE_TRANSFER_INSTALLED payload_bytes=%d counter=%d operations=%d payload_sha256=%s%n",
                    len, counter, operations, sha256(snapshotPayload));
        } catch (IOException e) {
            throw new IllegalStateException("cannot install snapshot", e);
        }
    }

    @Override
    public byte[] getSnapshot() {
        try {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream(snapshotPayload.length + 32);
            try (ObjectOutputStream out = new ObjectOutputStream(bytes)) {
                out.writeInt(counter);
                out.writeInt(operations);
                out.writeInt(snapshotPayload.length);
                out.write(snapshotPayload);
                out.flush();
            }
            return bytes.toByteArray();
        } catch (IOException e) {
            throw new IllegalStateException("cannot serialize snapshot", e);
        }
    }

    private static byte[] encode(int value) {
        try {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream(4);
            try (DataOutputStream out = new DataOutputStream(bytes)) {
                out.writeInt(value);
                out.flush();
            }
            return bytes.toByteArray();
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    private static String sha256(byte[] payload) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(payload);
            StringBuilder hex = new StringBuilder(64);
            for (byte b : digest) {
                hex.append(String.format("%02x", b));
            }
            return hex.toString();
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }

    public static void main(String[] args) {
        if (args.length != 2) {
            System.err.println("Usage: StatefulCounterServer <replica-id> <snapshot-bytes>");
            System.exit(2);
        }
        new StatefulCounterServer(Integer.parseInt(args[0]), Integer.parseInt(args[1]));
    }
}
