package progressrisk.bftsmart;

import bftsmart.reconfiguration.views.View;

import java.io.FileInputStream;
import java.io.ObjectInputStream;
import java.util.Arrays;

/**
 * Reads BFT-SMaRt's serialized config/currentView and checks exact view
 * membership. A2 uses this instead of grepping implementation log text.
 */
public final class ViewInspector {
    private ViewInspector() {
    }

    private static int[] parseMembers(String csv) {
        if (csv.isEmpty()) {
            return new int[0];
        }
        String[] parts = csv.split(",");
        int[] members = new int[parts.length];
        for (int i = 0; i < parts.length; i++) {
            members[i] = Integer.parseInt(parts[i].trim());
        }
        Arrays.sort(members);
        return members;
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 3) {
            System.err.println("Usage: ViewInspector <currentView-path> <expected-view-id> <expected-members-csv>");
            System.exit(2);
        }

        int expectedViewId = Integer.parseInt(args[1]);
        int[] expectedMembers = parseMembers(args[2]);
        try (ObjectInputStream in = new ObjectInputStream(new FileInputStream(args[0]))) {
            Object object = in.readObject();
            if (!(object instanceof View)) {
                throw new IllegalStateException("currentView does not contain a BFT-SMaRt View");
            }
            View view = (View) object;
            int[] actualMembers = view.getProcesses().clone();
            Arrays.sort(actualMembers);
            if (view.getId() != expectedViewId || !Arrays.equals(actualMembers, expectedMembers)) {
                throw new IllegalStateException(
                        "view mismatch: actual=id=" + view.getId() + " members=" + Arrays.toString(actualMembers)
                                + "; expected=id=" + expectedViewId + " members=" + Arrays.toString(expectedMembers));
            }
            System.out.printf("VIEW_OK id=%d members=%s%n", view.getId(), Arrays.toString(actualMembers));
        }
    }
}
