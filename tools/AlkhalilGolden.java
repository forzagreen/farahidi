import net.oujda_nlp_team.AlKhalil2Analyzer;
import net.oujda_nlp_team.entity.Result;
import net.oujda_nlp_team.entity.ResultList;

/**
 * Golden-output harness for AlKhalil Morpho Sys 2.
 * Reads one Arabic word per line on stdin, writes one JSON object per line on
 * stdout: {"word": "...", "analyses": [ {12 Result fields}, ... ]}.
 * Used to produce committed test fixtures for the `farahidi` Python port.
 */
public class AlkhalilGolden {

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

    static void f(StringBuilder sb, String k, String v, boolean comma) {
        sb.append('"').append(k).append("\":\"").append(esc(v)).append('"');
        if (comma) sb.append(',');
    }

    public static void main(String[] args) throws Exception {
        java.io.BufferedReader br =
            new java.io.BufferedReader(new java.io.InputStreamReader(System.in, "UTF-8"));
        java.io.PrintStream out = new java.io.PrintStream(System.out, true, "UTF-8");
        String word;
        while ((word = br.readLine()) != null) {
            word = word.trim();
            if (word.isEmpty()) continue;
            ResultList rl = AlKhalil2Analyzer.getInstance().processToken(word);
            StringBuilder sb = new StringBuilder();
            sb.append("{\"word\":\"").append(esc(word)).append("\",\"analyses\":[");
            boolean first = true;
            for (Result r : rl.getAllResults()) {
                if (!first) sb.append(',');
                first = false;
                sb.append('{');
                f(sb, "voweledWord", r.getVoweledWord(), true);
                f(sb, "proclitic", r.getProclitic(), true);
                f(sb, "stem", r.getStem(), true);
                f(sb, "partOfSpeech", r.getPartOfSpeech(), true);
                f(sb, "diacPatternStem", r.getDiacPatternStem(), true);
                f(sb, "patternStem", r.getPatternStem(), true);
                f(sb, "lemma", r.getLemma(), true);
                f(sb, "patternLemma", r.getPatternLemma(), true);
                f(sb, "root", r.getRoot(), true);
                f(sb, "caseOrMood", r.getCaseOrMood(), true);
                f(sb, "enclitic", r.getEnclitic(), true);
                f(sb, "priority", r.getPriority(), false);
                sb.append('}');
            }
            sb.append("]}");
            out.println(sb.toString());
        }
    }
}
