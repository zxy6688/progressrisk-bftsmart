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
 * Deterministic stateful service for the A1 BFT-SMaRt baseline.
 * It deliberately contains no membership change logic. The service exposes
 * ordered increments and serializes a fixed-size deterministic payload with
 * the counter state, so the next A2 gate can exercise state transfer.
 */
public final class StatefulCounterServer extends DefaultSingleRecoverable {
    private final int id;
    private int counter;
    private int operations;
    private byte[] snapshotPayload;

    public StatefulCounterServer(int id, int snapshotBytes) {
        if (snapshotBytes < 0) {
            throw new IllegalArgumentException("snapshotBytes must be nonnegative");
        }
        this.id = id;
        this.counter = 0;
        this.operations = 0;
        this.snapshotPayload = deterministicPayload(snapshotBytes);
        new ServiceReplica(id, this, this);
        System.out.printf(
                "STATEFUL_SERVICE_CONSTRUCTED id=%d snapshot_bytes=%d payload_sha256=%s%n",
                id, snapshotPayload.length, sha256(snapshotPayload));
    }

    @Override
    public synchronized byte[] appExecuteUnordered(byte[] command, MessageContext context) {
        System.out.printf(
                "STATEFUL_COUNTER_UNORDERED id=%d counter=%d operations=%d%n",
                id, counter, operations);
        return encodeCounter(counter);
    }

    @Override
    public synchronized byte[] appExecuteOrdered(byte[] command, MessageContext context) {
        final int increment;
        try {
            increment = new DataInputStream(new ByteArrayInputStream(command)).readInt();
        } catch (IOException e) {
            throw new IllegalArgumentException("invalid counter command", e);
        }

        counter += increment;
        operations += 1;
        System.out.printf(
                "STATEFUL_COUNTER_ORDERED id=%d counter=%d operations=%d%n",
                id, counter, operations);
        return encodeCounter(counter);
    }

    @Override
    public synchronized void installSnapshot(byte[] state) {
        try {
            ObjectInputStream in = new ObjectInputStream(new ByteArrayInputStream(state));
            int restoredCounter = in.readInt();
            int restoredOperations = in.readInt();
            int payloadLength = in.readInt();
            if (payloadLength < 0 || payloadLength > 64 * 1024 * 1024) {
                throw new IOException("invalid snapshot payload length: " + payloadLength);
            }
            byte[] restoredPayload = new byte[payloadLength];
            in.readFully(restoredPayload);
            in.close();

            counter = restoredCounter;
            operations = restoredOperations;
            snapshotPayload = restoredPayload;
            System.out.printf(
                    "STATE_TRANSFER_INSTALLED id=%d counter=%d operations=%d payload_bytes=%d payload_sha256=%s%n",
                    id, counter, operations, snapshotPayload.length, sha256(snapshotPayload));
        } catch (IOException e) {
            throw new IllegalStateException("cannot install stateful snapshot", e);
        }
    }

    @Override
    public synchronized byte[] getSnapshot() {
        try {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream(snapshotPayload.length + 64);
            ObjectOutputStream out = new ObjectOutputStream(bytes);
            out.writeInt(counter);
            out.writeInt(operations);
            out.writeInt(snapshotPayload.length);
            out.write(snapshotPayload);
            out.flush();
            out.close();
            System.out.printf(
                    "STATEFUL_SNAPSHOT_WRITTEN id=%d counter=%d operations=%d payload_bytes=%d payload_sha256=%s%n",
                    id, counter, operations, snapshotPayload.length, sha256(snapshotPayload));
            return bytes.toByteArray();
        } catch (IOException e) {
            throw new IllegalStateException("cannot serialize stateful snapshot", e);
        }
    }

    private static byte[] deterministicPayload(int length) {
        byte[] bytes = new byte[length];
        for (int i = 0; i < bytes.length; i++) {
            bytes[i] = (byte) (i % 251);
        }
        return bytes;
    }

    private static byte[] encodeCounter(int value) {
        try {
            ByteArrayOutputStream bytes = new ByteArrayOutputStream(4);
            DataOutputStream out = new DataOutputStream(bytes);
            out.writeInt(value);
            out.flush();
            return bytes.toByteArray();
        } catch (IOException e) {
            throw new IllegalStateException("cannot encode counter reply", e);
        }
    }

    private static String sha256(byte[] payload) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(payload);
            StringBuilder hex = new StringBuilder(digest.length * 2);
            for (byte b : digest) {
                hex.append(String.format("%02x", b & 0xff));
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
