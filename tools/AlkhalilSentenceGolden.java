import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import net.oujda_nlp_team.ADATAnalyzer;

/**
 * Golden-output harness for AlKhalil's in-context analyzer (Layer 2).
 * Reads one sentence per line on stdin; for each, runs the three shipped
 * disambiguators (lemmatizer / light stemmer / heavy stemmer) via the
 * deterministic string API and writes one JSON object per line on stdout:
 *   {"sentence","tokens":[...],"lemmas":[...],"stems":[...],"roots":[...]}
 *
 * These three calls share ADATAnalyzer.analyzed() for the lemma chain and use
 * the insertion-order (first-on-tie) getStems/getRoots selection — so the output
 * is reproducible and a faithful target for the farahidi Python port.
 */
public class AlkhalilSentenceGolden {

    private static final Pattern PAIR = Pattern.compile("\\{\\{(.*?)\\}\\}");

    static String esc(String s) {
        if (s == null) return "";
        StringBuilder b = new StringBuilder();
        for (char c : s.toCharArray()) {
            switch (c) {
                case '"':  b.append("\\\""); break;
                case '\\': b.append("\\\\"); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                default:   b.append(c);
            }
        }
        return b.toString();
    }

    /** Extract the value side of each {{token:value}} pair, in order. */
    static List<String[]> pairs(String result) {
        List<String[]> out = new ArrayList<>();
        Matcher m = PAIR.matcher(result);
        while (m.find()) {
            String inner = m.group(1);
            int i = inner.indexOf(':');
            if (i < 0) continue;
            out.add(new String[] { inner.substring(0, i), inner.substring(i + 1) });
        }
        return out;
    }

    static void arr(StringBuilder sb, String key, List<String> vals, boolean comma) {
        sb.append('"').append(key).append("\":[");
        for (int i = 0; i < vals.size(); i++) {
            if (i > 0) sb.append(',');
            sb.append('"').append(esc(vals.get(i))).append('"');
        }
        sb.append(']');
        if (comma) sb.append(',');
    }

    public static void main(String[] args) throws Exception {
        java.io.BufferedReader br =
            new java.io.BufferedReader(new java.io.InputStreamReader(System.in, "UTF-8"));
        java.io.PrintStream out = new java.io.PrintStream(System.out, true, "UTF-8");
        ADATAnalyzer ana = ADATAnalyzer.getInstance();
        String sentence;
        while ((sentence = br.readLine()) != null) {
            sentence = sentence.trim();
            if (sentence.isEmpty()) continue;

            List<String[]> lem = pairs(ana.processADATLemmatizerString(sentence));
            List<String[]> stem = pairs(ana.processADATStemmerString(sentence));
            List<String[]> root = pairs(ana.processADATRacineurString(sentence));

            List<String> tokens = new ArrayList<>();
            List<String> lemmas = new ArrayList<>();
            List<String> stems = new ArrayList<>();
            List<String> roots = new ArrayList<>();
            for (int i = 0; i < lem.size(); i++) {
                tokens.add(lem.get(i)[0]);
                lemmas.add(lem.get(i)[1]);
                stems.add(stem.get(i)[1]);
                roots.add(root.get(i)[1]);
            }

            StringBuilder sb = new StringBuilder();
            sb.append("{\"sentence\":\"").append(esc(sentence)).append("\",");
            arr(sb, "tokens", tokens, true);
            arr(sb, "lemmas", lemmas, true);
            arr(sb, "stems", stems, true);
            arr(sb, "roots", roots, false);
            sb.append('}');
            out.println(sb.toString());
        }
    }
}
