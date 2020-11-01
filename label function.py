
def label_reconcile(text_string, label_string):

#
#
#
    search_string = '.*- \[x\] ' + text_string + ' .*'
    negative_search_string = '.*- \[ ?\] ' + text_string + ' .*'
    print('--- Looking for ' + text_string + ' in description')
    if re.search(search_string, str(issue.body)):
        print("bug fix found in description")
        if label_string in existing_label_names:
            text_matched += 1
            print("*** bug fix label matched")
        else:
            print("*** bug fix label added")
            labels_to_add_table.add_row([pr_num, pr.title.strip(), label_string])
            labels_added += 1
            if update_labels:
                pr.add_to_labels(label_string)
    elif re.search(negative_search_string, str(issue.body)):
        print(label_string + " shouldn't be here - removing")
        labels_to_remove_table.add_row([pr_num, pr.title.strip(), label_string])
        labels_removed += 1
        if update_labels:
            pr.remove_from_labels(label_string)
